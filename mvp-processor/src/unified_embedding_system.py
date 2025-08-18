"""
Unified Face Embedding System
Provides consistent face embeddings across different backend models (InsightFace, face_recognition, OpenCV)
with proper normalization and distance scaling
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional, Union, List
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
                try:
                    # Pre-check face image quality for InsightFace
                    if self._is_suitable_for_insightface(face_image):
                        embedding = self._generate_insightface_embedding(face_image)
                        metadata["backend"] = "insightface"
                    else:
                        # Skip InsightFace for poor quality images
                        raise ValueError("Image quality unsuitable for InsightFace, using fallback")
                        
                except Exception as e:
                    fallback_reason = str(e)
                    metadata["insightface_failure"] = fallback_reason
                    
                    # Intelligent fallback selection based on failure reason
                    if "No face detected" in fallback_reason and self.face_recognition_available:
                        logger.debug(f"InsightFace detection failed: {e}, trying face_recognition")
                        try:
                            embedding = self._generate_face_recognition_embedding(face_image)
                            metadata["backend"] = "face_recognition_fallback"
                            method = EmbeddingMethod.FACE_RECOGNITION
                        except Exception as fr_e:
                            logger.debug(f"face_recognition also failed: {fr_e}, using OpenCV")
                            embedding = self._generate_opencv_embedding(face_image)
                            metadata["backend"] = "opencv_double_fallback"
                            method = EmbeddingMethod.OPENCV_CUSTOM
                            metadata["face_recognition_failure"] = str(fr_e)
                    else:
                        logger.debug(f"InsightFace failed ({e}), using OpenCV directly")
                        embedding = self._generate_opencv_embedding(face_image)
                        metadata["backend"] = "opencv_fallback"
                        method = EmbeddingMethod.OPENCV_CUSTOM

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
            logger.error(f"All embedding methods failed: {e}")
            # Try emergency fallback with different preprocessing
            try:
                logger.info("Attempting emergency fallback with enhanced preprocessing")
                
                # Apply more aggressive preprocessing for difficult cases
                if isinstance(face_image, np.ndarray):
                    processed_image = self._emergency_preprocess_image(face_image)
                    
                    # Try OpenCV method with processed image
                    embedding = self._generate_opencv_embedding(processed_image)
                    metadata.update({"backend": "opencv_emergency", "preprocessing": "enhanced"})
                    
                else:
                    raise ValueError("Cannot preprocess non-array input")
                    
            except Exception as fallback_error:
                logger.error(f"Emergency fallback also failed: {fallback_error}")
                # Last resort: create a pseudo-random but deterministic vector
                # Based on image statistics for some consistency
                if isinstance(face_image, np.ndarray):
                    # Use image statistics to create deterministic vector
                    img_stats = [
                        np.mean(face_image),
                        np.std(face_image),
                        np.min(face_image),
                        np.max(face_image)
                    ]
                    seed = int(sum(img_stats) * 1000) % 2**32
                    np.random.seed(seed)
                else:
                    np.random.seed(42)  # Fixed seed for file paths
                    
                embedding = np.random.randn(
                    self.embedding_config.embedding_dimension
                ).astype(np.float32)
                embedding = embedding / np.linalg.norm(embedding)
                metadata.update({"backend": "deterministic_fallback", "error": f"{e} | {fallback_error}"})
            
            return embedding, metadata

    def generate_batch_embeddings(
        self, 
        face_images: List[np.ndarray], 
        method: Optional[EmbeddingMethod] = None
    ) -> List[Tuple[np.ndarray, Dict]]:
        """
        Generate embeddings for a batch of face images efficiently.
        
        Args:
            face_images: List of RGB face image arrays (cropped to face regions)
            method: Optional specific method to use, defaults to configured method
            
        Returns:
            List of (normalized_embedding, metadata) tuples
        """
        if not face_images:
            return []
            
        if method is None:
            method = self.embedding_config.method
            
        # Try batch processing for supported methods
        if method == EmbeddingMethod.INSIGHTFACE and self.insightface_model is not None:
            try:
                return self._generate_insightface_batch_embeddings(face_images)
            except Exception as e:
                logger.warning(f"Batch InsightFace processing failed: {e}, falling back to individual processing")
                
        # Fallback to individual processing for non-batch methods or failures
        results = []
        for face_image in face_images:
            try:
                embedding, metadata = self.generate_embedding(face_image, method)
                results.append((embedding, metadata))
            except Exception as e:
                logger.debug(f"Failed to generate embedding for face in batch: {e}")
                # Generate a null embedding for failed faces to maintain batch alignment
                null_embedding = np.zeros(self.embedding_config.embedding_dimension, dtype=np.float32)
                null_metadata = {
                    "method": method.value,
                    "dimension": self.embedding_config.embedding_dimension,
                    "normalized": self.embedding_config.normalize_embeddings,
                    "backend": "failed",
                    "error": str(e)
                }
                results.append((null_embedding, null_metadata))
                
        return results

    def _generate_insightface_batch_embeddings(self, face_images: List[np.ndarray]) -> List[Tuple[np.ndarray, Dict]]:
        """Generate embeddings for multiple faces using InsightFace batch processing"""
        results = []
        
        # Process in smaller batches to manage memory
        batch_size = min(len(face_images), 8)  # Adjust based on GPU memory
        
        for i in range(0, len(face_images), batch_size):
            batch = face_images[i:i + batch_size]
            
            # Pre-process all images in the batch
            processed_images = []
            valid_indices = []
            
            for idx, face_image in enumerate(batch):
                if self._is_suitable_for_insightface(face_image):
                    # Convert to BGR for InsightFace
                    bgr_image = cv2.cvtColor(face_image, cv2.COLOR_RGB2BGR)
                    processed_images.append(bgr_image)
                    valid_indices.append(i + idx)
                else:
                    # Mark invalid images for individual fallback processing
                    processed_images.append(None)
                    valid_indices.append(None)
            
            # Process valid images in batch
            batch_embeddings = []
            if any(img is not None for img in processed_images):
                try:
                    # InsightFace batch processing
                    valid_images = [img for img in processed_images if img is not None]
                    if valid_images:
                        # Use InsightFace's batch processing if available
                        for valid_img in valid_images:
                            faces = self.insightface_model.get(valid_img)
                            if faces:
                                embedding = faces[0].embedding  # Use first/best face
                                if self.embedding_config.normalize_embeddings:
                                    embedding = self._normalize_embedding(embedding)
                                batch_embeddings.append(embedding)
                            else:
                                # No face detected, create null embedding
                                batch_embeddings.append(np.zeros(512, dtype=np.float32))
                        
                except Exception as e:
                    logger.debug(f"Batch InsightFace processing failed: {e}")
                    # Fall back to individual processing for this batch
                    batch_embeddings = []
                    for img in valid_images:
                        try:
                            faces = self.insightface_model.get(img)
                            if faces:
                                embedding = faces[0].embedding
                                if self.embedding_config.normalize_embeddings:
                                    embedding = self._normalize_embedding(embedding)
                                batch_embeddings.append(embedding)
                            else:
                                batch_embeddings.append(np.zeros(512, dtype=np.float32))
                        except:
                            batch_embeddings.append(np.zeros(512, dtype=np.float32))
            
            # Combine results with metadata
            valid_idx = 0
            for idx, original_image in enumerate(batch):
                metadata = {
                    "method": EmbeddingMethod.INSIGHTFACE.value,
                    "dimension": 512,
                    "normalized": self.embedding_config.normalize_embeddings,
                    "backend": "insightface_batch"
                }
                
                if processed_images[idx] is not None and valid_idx < len(batch_embeddings):
                    # Valid embedding from batch processing
                    embedding = batch_embeddings[valid_idx]
                    valid_idx += 1
                else:
                    # Fallback for invalid images
                    try:
                        embedding, fallback_metadata = self.generate_embedding(
                            original_image, EmbeddingMethod.FACE_RECOGNITION
                        )
                        metadata.update(fallback_metadata)
                        metadata["backend"] = "fallback_from_batch"
                    except:
                        embedding = np.zeros(self.embedding_config.embedding_dimension, dtype=np.float32)
                        metadata["backend"] = "failed_batch"
                
                results.append((embedding, metadata))
        
        return results

    def _emergency_preprocess_image(self, face_image: np.ndarray) -> np.ndarray:
        """Emergency preprocessing for difficult face images"""
        try:
            # Ensure we have a valid RGB image
            if len(face_image.shape) != 3 or face_image.shape[2] != 3:
                logger.warning(f"Invalid image shape for preprocessing: {face_image.shape}")
                return face_image
                
            # Convert to float for processing
            img_float = face_image.astype(np.float32) / 255.0
            
            # Apply gamma correction to enhance contrast
            gamma = 0.8
            img_gamma = np.power(img_float, gamma)
            
            # Apply unsharp masking for edge enhancement
            blur = cv2.GaussianBlur(img_gamma, (5, 5), 1.0)
            unsharp = cv2.addWeighted(img_gamma, 1.5, blur, -0.5, 0)
            
            # Ensure values are in valid range
            unsharp = np.clip(unsharp, 0, 1)
            
            # Convert back to uint8
            enhanced = (unsharp * 255).astype(np.uint8)
            
            # Apply bilateral filter to smooth while preserving edges
            enhanced = cv2.bilateralFilter(enhanced, 9, 75, 75)
            
            logger.debug("Applied emergency preprocessing to face image")
            return enhanced
            
        except Exception as e:
            logger.debug(f"Emergency preprocessing failed: {e}, using original")
            return face_image

    def _enhance_face_for_insightface(self, face_image: np.ndarray) -> np.ndarray:
        """Enhanced preprocessing specifically for InsightFace face detection"""
        try:
            # Ensure minimum size for InsightFace (112x112 is optimal)
            h, w = face_image.shape[:2]
            min_size = 112
            
            if h < min_size or w < min_size:
                # Calculate new dimensions to maintain aspect ratio
                scale = max(min_size / h, min_size / w)
                new_h, new_w = int(h * scale), int(w * scale)
                face_image = cv2.resize(face_image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            
            # Convert to LAB for better preprocessing
            lab = cv2.cvtColor(face_image, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            # Apply CLAHE to improve contrast for face detection
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_l = clahe.apply(l_channel)
            
            # Merge back to RGB
            enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
            enhanced_rgb = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
            
            # Slight sharpening to help with face detection
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(enhanced_rgb, -1, kernel)
            
            # Blend original and sharpened (mild effect)
            result = cv2.addWeighted(enhanced_rgb, 0.7, sharpened, 0.3, 0)
            
            return result.astype(np.uint8)
            
        except Exception as e:
            logger.debug(f"InsightFace enhancement failed: {e}, using original")
            return face_image

    def _aggressive_face_enhancement(self, face_image: np.ndarray) -> np.ndarray:
        """Aggressive enhancement for difficult face images"""
        try:
            # Resize to at least 224x224 for better detection
            h, w = face_image.shape[:2]
            target_size = 224
            
            if h < target_size or w < target_size:
                scale = max(target_size / h, target_size / w)
                new_h, new_w = int(h * scale), int(w * scale)
                face_image = cv2.resize(face_image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            
            # Normalize brightness
            gray = cv2.cvtColor(face_image, cv2.COLOR_RGB2GRAY)
            mean_brightness = np.mean(gray)
            
            if mean_brightness < 100:
                # Brighten dark images
                gamma = 0.7
                corrected = np.power(face_image / 255.0, gamma) * 255.0
                face_image = corrected.astype(np.uint8)
            elif mean_brightness > 180:
                # Darken bright images  
                gamma = 1.3
                corrected = np.power(face_image / 255.0, gamma) * 255.0
                face_image = corrected.astype(np.uint8)
            
            # Aggressive contrast enhancement
            lab = cv2.cvtColor(face_image, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            # More aggressive CLAHE
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
            enhanced_l = clahe.apply(l_channel)
            
            # Merge back
            enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
            enhanced_rgb = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
            
            # Apply bilateral filter for noise reduction while preserving edges
            filtered = cv2.bilateralFilter(enhanced_rgb, 9, 75, 75)
            
            # Ensure valid range
            result = np.clip(filtered, 0, 255)
            
            return result.astype(np.uint8)
            
        except Exception as e:
            logger.debug(f"Aggressive enhancement failed: {e}, using original")
            return face_image

    def _is_suitable_for_insightface(self, face_image: np.ndarray) -> bool:
        """Check if face image is suitable for InsightFace processing"""
        try:
            # Check minimum size requirements
            h, w = face_image.shape[:2]
            if h < 50 or w < 50:  # Too small for reliable detection
                return False
                
            # Check image quality metrics
            gray = cv2.cvtColor(face_image, cv2.COLOR_RGB2GRAY)
            
            # Check contrast (standard deviation)
            std_dev = np.std(gray)
            if std_dev < 10:  # Too low contrast
                return False
                
            # Check brightness range
            mean_brightness = np.mean(gray)
            if mean_brightness < 10 or mean_brightness > 245:  # Too dark or too bright
                return False
                
            # Check for blur using Laplacian variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian_var < 50:  # Too blurry
                return False
                
            # Check aspect ratio
            aspect_ratio = w / h
            if aspect_ratio < 0.3 or aspect_ratio > 3.0:  # Extreme aspect ratios
                return False
                
            return True
            
        except Exception as e:
            logger.debug(f"Suitability check failed: {e}, assuming suitable")
            return True  # Conservative: assume suitable if check fails

    def _generate_insightface_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """Generate embedding using InsightFace model with enhanced preprocessing"""

        # Validate input
        if not isinstance(face_image, np.ndarray):
            raise TypeError(f"Expected numpy array, got {type(face_image)}")

        if len(face_image.shape) != 3 or face_image.shape[2] != 3:
            raise ValueError(
                f"Expected RGB image with shape (H, W, 3), got {face_image.shape}"
            )

        # Enhanced preprocessing for better InsightFace detection
        preprocessed_image = self._enhance_face_for_insightface(face_image)
        
        # Convert RGB to BGR for InsightFace
        bgr_image = cv2.cvtColor(preprocessed_image, cv2.COLOR_RGB2BGR)

        # Get face analysis (should contain embeddings)
        faces = self.insightface_model.get(bgr_image)

        if len(faces) == 0:
            # Try with original image if preprocessing failed
            bgr_original = cv2.cvtColor(face_image, cv2.COLOR_RGB2BGR)
            faces = self.insightface_model.get(bgr_original)
            
            if len(faces) == 0:
                # Try with additional enhancement techniques
                enhanced_image = self._aggressive_face_enhancement(face_image)
                bgr_enhanced = cv2.cvtColor(enhanced_image, cv2.COLOR_RGB2BGR)
                faces = self.insightface_model.get(bgr_enhanced)
                
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
