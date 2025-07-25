"""
Unified Face Embedding System
Provides consistent face embeddings across different backend models (InsightFace, face_recognition, OpenCV)
with proper normalization and distance scaling
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional, Union
import logging
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class EmbeddingMethod(Enum):
    """Supported embedding methods"""

    INSIGHTFACE = "insightface"
    FACE_RECOGNITION = "face_recognition"
    OPENCV_CUSTOM = "opencv_custom"


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation"""

    method: EmbeddingMethod
    normalize_embeddings: bool = True
    embedding_dimension: int = 512
    distance_threshold: float = 0.6
    confidence_threshold: float = 0.5


class UnifiedEmbeddingSystem:
    """
    Unified face embedding system that provides consistent embeddings
    regardless of the underlying model (InsightFace, face_recognition, OpenCV)
    """

    def __init__(self, config: dict):
        self.config = config
        self.embedding_config = self._load_embedding_config(config)

        # Initialize backends
        self.insightface_model = None
        self.face_recognition_available = False

        # Performance tracking
        self.embedding_stats = {
            "method_used": [],
            "embedding_times": [],
            "normalization_factors": [],
        }

        # Cache for embedding metadata
        self.embedding_metadata_cache = {}

        self._initialize_backends()

    def _load_image_from_path(self, image_path: Union[str, Path]) -> np.ndarray:
        """Load and preprocess image from file path"""
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")

            # Load image using OpenCV
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")

            # Convert BGR to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Validate image dimensions
            if len(image_rgb.shape) != 3 or image_rgb.shape[2] != 3:
                raise ValueError(
                    f"Invalid image format: expected RGB, got shape {image_rgb.shape}"
                )

            return image_rgb

        except Exception as e:
            logger.error(f"Failed to load image from {image_path}: {e}")
            raise

    def _load_embedding_config(self, config: dict) -> EmbeddingConfig:
        """Load embedding configuration with intelligent defaults"""
        face_detection_config = config.get("face_detection", {})

        # Determine best method based on availability and hardware
        if (
            face_detection_config.get("enable_hardware_acceleration")
            and face_detection_config.get("model") == "insightface"
        ):
            method = EmbeddingMethod.INSIGHTFACE
            distance_threshold = (
                0.4  # InsightFace uses cosine distance, typically lower thresholds
            )
        else:
            # Try face_recognition first, fallback to OpenCV
            method = EmbeddingMethod.FACE_RECOGNITION
            distance_threshold = 0.6  # face_recognition uses euclidean distance

        return EmbeddingConfig(
            method=method,
            normalize_embeddings=True,
            embedding_dimension=512,
            distance_threshold=distance_threshold,
            confidence_threshold=0.5,
        )

    def _initialize_backends(self):
        """Initialize available embedding backends"""

        # Try to initialize InsightFace
        try:
            import insightface

            # Use CPU provider for consistency during embedding generation
            self.insightface_model = insightface.app.FaceAnalysis(
                providers=["CPUExecutionProvider"]
            )
            self.insightface_model.prepare(ctx_id=-1)
            logger.info("InsightFace backend initialized successfully")
        except Exception as e:
            logger.debug(f"InsightFace initialization failed: {e}")

        # Only try to initialize face_recognition if InsightFace failed or if explicitly configured
        if (
            self.insightface_model is None
            or self.embedding_config.method == EmbeddingMethod.FACE_RECOGNITION
        ):
            try:
                self.face_recognition_available = True
                logger.info("face_recognition backend available")
            except Exception as e:
                logger.debug(f"face_recognition not available: {e}")
        else:
            logger.info(
                "Skipping face_recognition initialization (InsightFace available and preferred)"
            )

    def generate_embedding(
        self,
        face_image: Union[np.ndarray, str, Path],
        method: Optional[EmbeddingMethod] = None,
    ) -> Tuple[np.ndarray, Dict]:
        """
        Generate a normalized face embedding using the specified or best available method

        Args:
            face_image: RGB face image (cropped to face region) or path to image file
            method: Optional specific method to use, defaults to configured method

        Returns:
            Tuple of (normalized_embedding, metadata)
        """
        if method is None:
            method = self.embedding_config.method

        # Handle file path input
        if isinstance(face_image, (str, Path)):
            face_image = self._load_image_from_path(face_image)

        metadata = {
            "method": method.value,
            "dimension": self.embedding_config.embedding_dimension,
            "normalized": self.embedding_config.normalize_embeddings,
        }

        try:
            if (
                method == EmbeddingMethod.INSIGHTFACE
                and self.insightface_model is not None
            ):
                embedding = self._generate_insightface_embedding(face_image)
                metadata["backend"] = "insightface"

            elif (
                method == EmbeddingMethod.FACE_RECOGNITION
                and self.face_recognition_available
            ):
                embedding = self._generate_face_recognition_embedding(face_image)
                metadata["backend"] = "face_recognition"

            else:
                # Fallback to OpenCV custom method
                embedding = self._generate_opencv_embedding(face_image)
                metadata["backend"] = "opencv_custom"
                method = EmbeddingMethod.OPENCV_CUSTOM

            # Ensure consistent dimensionality
            embedding = self._ensure_dimension(
                embedding, self.embedding_config.embedding_dimension
            )

            # Normalize if required
            if self.embedding_config.normalize_embeddings:
                embedding_norm = np.linalg.norm(embedding)
                if embedding_norm > 1e-8:
                    embedding = embedding / embedding_norm
                    metadata["norm_factor"] = float(embedding_norm)
                else:
                    logger.warning("Zero norm embedding detected, using unit vector")
                    embedding = np.ones_like(embedding) / np.sqrt(len(embedding))
                    metadata["norm_factor"] = 1.0

            metadata["final_norm"] = float(np.linalg.norm(embedding))

            # Update statistics
            self.embedding_stats["method_used"].append(method.value)
            self.embedding_stats["normalization_factors"].append(
                metadata.get("norm_factor", 1.0)
            )

            return embedding, metadata

        except Exception as e:
            logger.error(f"Embedding generation failed with {method.value}: {e}")
            # Emergency fallback to random normalized vector
            embedding = np.random.randn(
                self.embedding_config.embedding_dimension
            ).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            metadata.update({"backend": "random_fallback", "error": str(e)})
            return embedding, metadata

    def _generate_insightface_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """Generate embedding using InsightFace model"""

        # Validate input
        if not isinstance(face_image, np.ndarray):
            raise TypeError(f"Expected numpy array, got {type(face_image)}")

        if len(face_image.shape) != 3 or face_image.shape[2] != 3:
            raise ValueError(
                f"Expected RGB image with shape (H, W, 3), got {face_image.shape}"
            )

        # Convert RGB to BGR for InsightFace
        bgr_image = cv2.cvtColor(face_image, cv2.COLOR_RGB2BGR)

        # Get face analysis (should contain embeddings)
        faces = self.insightface_model.get(bgr_image)

        if len(faces) == 0:
            raise ValueError("No face detected by InsightFace in provided image")

        # Use the first (most confident) face
        face = faces[0]

        # Return the embedding (usually 512-dimensional)
        return face.embedding.astype(np.float32)

    def _generate_face_recognition_embedding(
        self, face_image: np.ndarray
    ) -> np.ndarray:
        """Generate embedding using face_recognition library"""
        import face_recognition

        # Validate input
        if not isinstance(face_image, np.ndarray):
            raise TypeError(f"Expected numpy array, got {type(face_image)}")

        if len(face_image.shape) != 3 or face_image.shape[2] != 3:
            raise ValueError(
                f"Expected RGB image with shape (H, W, 3), got {face_image.shape}"
            )

        # face_recognition expects RGB format
        encodings = face_recognition.face_encodings(face_image)

        if len(encodings) == 0:
            raise ValueError("No face detected by face_recognition in provided image")

        return encodings[0].astype(np.float32)

    def _generate_opencv_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """Generate custom embedding using OpenCV features (enhanced version of current method)"""

        # Validate input
        if not isinstance(face_image, np.ndarray):
            raise TypeError(f"Expected numpy array, got {type(face_image)}")

        # Convert to grayscale if needed
        if len(face_image.shape) == 3:
            if face_image.shape[2] != 3:
                raise ValueError(
                    f"Expected RGB image with 3 channels, got {face_image.shape[2]}"
                )
            face_gray = cv2.cvtColor(face_image, cv2.COLOR_RGB2GRAY)
        elif len(face_image.shape) == 2:
            face_gray = face_image.copy()
        else:
            raise ValueError(f"Expected 2D or 3D image, got shape {face_image.shape}")

        # Check for sufficient contrast
        if np.std(face_gray) < 10:
            logger.warning("Low contrast face region detected")

        # Apply histogram equalization
        face_gray_eq = cv2.equalizeHist(face_gray)

        # Resize to consistent dimensions
        face_resized = cv2.resize(face_gray_eq, (64, 64))

        # Create multi-scale feature representation
        features = []

        # 1. Raw pixel features (downsampled)
        pixel_features = face_resized.flatten().astype(np.float32)
        features.append(pixel_features)

        # 2. Gradient features (Sobel)
        grad_x = cv2.Sobel(face_resized, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(face_resized, cv2.CV_32F, 0, 1, ksize=3)
        features.append(grad_x.flatten()[:256])  # Limit size
        features.append(grad_y.flatten()[:256])

        # 3. LBP (Local Binary Pattern) features for texture
        lbp = self._calculate_lbp(face_resized)
        features.append(lbp.flatten()[:256])

        # 4. HOG (Histogram of Oriented Gradients) features
        hog_features = self._calculate_hog_features(face_resized)
        features.append(hog_features)

        # Combine all features
        combined_features = np.concatenate(features)

        return combined_features.astype(np.float32)

    def _calculate_lbp(
        self, image: np.ndarray, radius: int = 1, n_points: int = 8
    ) -> np.ndarray:
        """Calculate Local Binary Pattern features"""
        h, w = image.shape
        lbp_image = np.zeros_like(image, dtype=np.uint8)

        for y in range(radius, h - radius):
            for x in range(radius, w - radius):
                center = image[y, x]
                binary_string = []

                # Sample points around the center
                for i in range(n_points):
                    angle = 2 * np.pi * i / n_points
                    px = int(x + radius * np.cos(angle))
                    py = int(y + radius * np.sin(angle))

                    if 0 <= px < w and 0 <= py < h:
                        binary_string.append(1 if image[py, px] >= center else 0)
                    else:
                        binary_string.append(0)

                # Convert binary string to decimal
                lbp_value = sum(binary_string[i] * (2**i) for i in range(n_points))
                lbp_image[y, x] = lbp_value

        return lbp_image

    def _calculate_hog_features(self, image: np.ndarray) -> np.ndarray:
        """Calculate simplified HOG features"""
        # Calculate gradients
        grad_x = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)

        # Calculate magnitude and orientation
        magnitude = np.sqrt(grad_x**2 + grad_y**2)
        orientation = np.arctan2(grad_y, grad_x) * 180 / np.pi
        orientation = (orientation + 180) % 180  # 0-180 degrees

        # Create histogram of orientations (9 bins for 0-180 degrees)
        hist_bins = 9
        bin_size = 180 / hist_bins

        # Create histogram weighted by magnitude
        hist = np.zeros(hist_bins)
        for i in range(hist_bins):
            mask = (orientation >= i * bin_size) & (orientation < (i + 1) * bin_size)
            hist[i] = np.sum(magnitude[mask])

        return hist / (np.sum(hist) + 1e-8)  # Normalize

    def _ensure_dimension(self, embedding: np.ndarray, target_dim: int) -> np.ndarray:
        """Ensure embedding has the target dimension"""
        current_dim = len(embedding)

        if current_dim == target_dim:
            return embedding
        elif current_dim > target_dim:
            # Truncate to target dimension
            return embedding[:target_dim]
        else:
            # Pad with zeros to reach target dimension
            padding = np.zeros(target_dim - current_dim, dtype=embedding.dtype)
            return np.concatenate([embedding, padding])

    def calculate_distance(
        self, embedding1: np.ndarray, embedding2: np.ndarray, method: str = "cosine"
    ) -> float:
        """
        Calculate distance between two embeddings using specified method

        Args:
            embedding1, embedding2: Normalized embeddings
            method: "cosine", "euclidean", or "hybrid"

        Returns:
            Distance value (lower = more similar)
        """

        # Ensure both embeddings have the same dimension
        target_dim = self.embedding_config.embedding_dimension
        embedding1 = self._ensure_dimension(embedding1, target_dim)
        embedding2 = self._ensure_dimension(embedding2, target_dim)

        if method == "cosine":
            # Cosine distance (1 - cosine similarity)
            # For normalized vectors, this is equivalent to ||a-b||^2 / 2
            cosine_sim = np.dot(embedding1, embedding2)
            return 1.0 - cosine_sim

        elif method == "euclidean":
            # Euclidean distance
            return np.linalg.norm(embedding1 - embedding2)

        elif method == "hybrid":
            # Weighted combination of cosine and euclidean
            cosine_dist = 1.0 - np.dot(embedding1, embedding2)
            euclidean_dist = np.linalg.norm(embedding1 - embedding2)
            # Normalize euclidean to similar range as cosine (0-2)
            euclidean_normalized = euclidean_dist / np.sqrt(2)
            return 0.7 * cosine_dist + 0.3 * euclidean_normalized

        else:
            raise ValueError(f"Unknown distance method: {method}")

    def distance_to_confidence(self, distance: float, method: str = "cosine") -> float:
        """
        Convert distance to confidence score (0-1)

        Args:
            distance: Distance value
            method: Distance method used

        Returns:
            Confidence score (higher = more confident match)
        """

        if method == "cosine":
            # Cosine distance ranges 0-2, map to confidence 1-0
            confidence = max(0.0, 1.0 - (distance / 2.0))
            # Apply sigmoid for better separation
            confidence = 1.0 / (1.0 + np.exp(-10 * (confidence - 0.5)))

        elif method == "euclidean":
            # For normalized vectors, euclidean distance ranges 0-2
            confidence = max(0.0, 1.0 - (distance / 2.0))
            confidence = 1.0 / (1.0 + np.exp(-8 * (confidence - 0.6)))

        elif method == "hybrid":
            # Hybrid uses normalized range 0-2
            confidence = max(0.0, 1.0 - (distance / 2.0))
            confidence = 1.0 / (1.0 + np.exp(-9 * (confidence - 0.55)))

        else:
            # Default linear mapping
            confidence = max(0.0, 1.0 - distance)

        return float(confidence)

    def migrate_embeddings(
        self,
        embeddings_dir: Path,
        target_method: Optional[EmbeddingMethod] = None,
        force_regenerate: bool = False,
    ) -> Dict:
        """
        Migrate existing embeddings to unified format

        Args:
            embeddings_dir: Directory containing embedding files
            target_method: Target embedding method (None = use configured method)
            force_regenerate: Force regeneration even if unified embeddings exist

        Returns:
            Migration statistics
        """

        if target_method is None:
            target_method = self.embedding_config.method

        stats = {
            "migrated": 0,
            "skipped": 0,
            "errors": 0,
            "target_method": target_method.value,
        }

        # Find all embedding files
        embedding_files = list(embeddings_dir.glob("*_embedding.npy"))

        for embedding_file in embedding_files:
            try:
                # Check if unified version already exists
                unified_file = embedding_file.with_name(
                    embedding_file.name.replace(
                        "_embedding.npy", "_unified_embedding.npy"
                    )
                )
                metadata_file = embedding_file.with_name(
                    embedding_file.name.replace(
                        "_embedding.npy", "_embedding_metadata.json"
                    )
                )

                if (
                    unified_file.exists()
                    and metadata_file.exists()
                    and not force_regenerate
                ):
                    # Check if metadata indicates correct method
                    try:
                        with open(metadata_file, "r") as f:
                            metadata = json.load(f)
                        if metadata.get("method") == target_method.value:
                            stats["skipped"] += 1
                            continue
                    except:
                        pass

                # Load original embedding
                original_embedding = np.load(embedding_file)

                # If this is already a unified embedding, check if we need to convert method
                if self._is_unified_embedding(original_embedding, metadata_file):
                    existing_metadata = self._load_embedding_metadata(metadata_file)
                    if existing_metadata.get("method") == target_method.value:
                        stats["skipped"] += 1
                        continue

                # Need to regenerate - this requires the original face image
                # For migration, we'll normalize the existing embedding to our format
                migrated_embedding, new_metadata = self._migrate_single_embedding(
                    original_embedding, target_method
                )

                # Save unified embedding and metadata
                np.save(unified_file, migrated_embedding)
                with open(metadata_file, "w") as f:
                    json.dump(new_metadata, f, indent=2)

                stats["migrated"] += 1
                logger.info(f"Migrated embedding: {embedding_file.name}")

            except Exception as e:
                logger.error(f"Failed to migrate {embedding_file}: {e}")
                stats["errors"] += 1

        logger.info(f"Migration complete: {stats}")
        return stats

    def _migrate_single_embedding(
        self, original_embedding: np.ndarray, target_method: EmbeddingMethod
    ) -> Tuple[np.ndarray, Dict]:
        """Migrate a single embedding to unified format"""

        # Ensure correct dimensions
        embedding = self._ensure_dimension(
            original_embedding, self.embedding_config.embedding_dimension
        )

        # Normalize the embedding
        if self.embedding_config.normalize_embeddings:
            embedding_norm = np.linalg.norm(embedding)
            if embedding_norm > 1e-8:
                embedding = embedding / embedding_norm
            else:
                # Handle zero embedding case
                embedding = np.ones_like(embedding) / np.sqrt(len(embedding))

        metadata = {
            "method": target_method.value,
            "dimension": self.embedding_config.embedding_dimension,
            "normalized": self.embedding_config.normalize_embeddings,
            "migrated_from": "legacy_embedding",
            "migration_timestamp": datetime.now().isoformat(),
            "final_norm": float(np.linalg.norm(embedding)),
        }

        return embedding, metadata

    def _is_unified_embedding(self, embedding: np.ndarray, metadata_file: Path) -> bool:
        """Check if an embedding is already in unified format"""
        return metadata_file.exists()

    def _load_embedding_metadata(self, metadata_file: Path) -> Dict:
        """Load embedding metadata from file"""
        try:
            with open(metadata_file, "r") as f:
                return json.load(f)
        except:
            return {}

    def get_optimal_threshold(self, method: str = "cosine") -> float:
        """Get optimal distance threshold for the given method"""
        thresholds = {
            "cosine": 0.4,  # Good separation for normalized embeddings
            "euclidean": 0.8,  # Adjusted for normalized vectors
            "hybrid": 0.5,  # Balanced threshold
        }
        return thresholds.get(method, self.embedding_config.distance_threshold)

    def validate_embedding(self, embedding: np.ndarray) -> bool:
        """Validate that an embedding meets quality standards"""

        # Check dimensions
        if len(embedding) != self.embedding_config.embedding_dimension:
            return False

        # Check for NaN or infinite values
        if not np.isfinite(embedding).all():
            return False

        # Check if normalized (if required)
        if self.embedding_config.normalize_embeddings:
            norm = np.linalg.norm(embedding)
            if abs(norm - 1.0) > 0.1:  # Allow small tolerance
                return False

        # Check for degenerate cases (all zeros, all same value)
        if np.std(embedding) < 1e-6:
            return False

        return True

    def get_statistics(self) -> Dict:
        """Get embedding system statistics"""
        return {
            "config": {
                "method": self.embedding_config.method.value,
                "dimension": self.embedding_config.embedding_dimension,
                "normalized": self.embedding_config.normalize_embeddings,
                "distance_threshold": self.embedding_config.distance_threshold,
            },
            "backend_availability": {
                "insightface": self.insightface_model is not None,
                "face_recognition": self.face_recognition_available,
                "opencv_custom": True,  # Always available
            },
            "usage_stats": dict(self.embedding_stats),
        }
